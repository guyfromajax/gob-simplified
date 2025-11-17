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
        this.gameId = gameStore.getGameId();
        if (!this.gameId && typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
        this.quarter = data.quarter || 1;
        this.gamePlanSettings = data.gamePlanSettings;
        this.userTeamSide = data.userTeamSide;
        
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
        this.load.image("ball", "/static/images/ball.png");
        const { home } = gameStore.getTeams();
        const normalizeTeamName = (name) => name.toLowerCase().replace(/[\s\-]/g, '_');
        const teamId = normalizeTeamName(home);
        this.load.image("court-bg", `/static/images/courts/${teamId}.jpg`);
      }

    }

    async create() {
      if (DEBUG_FLOW) console.log("🎬 GameScene created");
      
      // Expose gameScene globally for Playcall Center tooltips
      window.currentGameScene = this;
      
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

      const payload = { home_team: homeTeam, away_team: awayTeam, quarter: this.quarter };
      if (this.gameId) payload.game_id = this.gameId;
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
      
      // Add game plan settings for Q1
      if (this.quarter === 1 && this.gamePlanSettings && this.userTeamSide) {
        payload.user_team_side = this.userTeamSide;
        payload.playcall_settings = this.gamePlanSettings.playcall_settings;
        payload.strategy_settings = this.gamePlanSettings.strategy_settings;
      } else if (this.quarter === 1) {
        console.warn('⚠️ [gameScene] Not sending game plan:', { 
          hasSettings: !!this.gamePlanSettings, 
          userTeamSide: this.userTeamSide 
        });
      }
      
      // Note: Q4 possession is handled by backend using opening_tip_winner from Q1
      // No need to pass start_with_inbound for standard Q4 logic
      const url = this.gameId || this.quarter > 1 ? '/api/simulate-quarter' : '/api/simulate-quarter';
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
      DEBUG && console.log('[gameScene] simData.turns', simData.turns.length, simData.turns[0]);
      if (DEBUG_FLOW) {
        console.log("📦 simData received:", simData);
        const turnsLen = Array.isArray(simData.turns) ? simData.turns.length : 0;
        console.log('🔄 Sim response arrived', { turns: turnsLen });
      }
      DEBUG_FLOW && console.log('[gameScene] quarters', { requested: this.quarter, sim: simData.quarter });
      
      // Handle both new (nested) and old (flat) structure
      const homeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
      const awayTeamObj = typeof simData.away_team === 'object' ? simData.away_team : null;
      
      // Extract team names (new nested structure or old flat structure)
      const logHome = homeTeamObj?.name || simData.home_team || simData.homeTeam?.name;
      const logAway = awayTeamObj?.name || simData.away_team || simData.awayTeam?.name;
      
      // Extract team IDs
      const homeId = homeTeamObj?.team_id || simData.home_team_id || simData.homeTeam?.team_id;
      const awayId = awayTeamObj?.team_id || simData.away_team_id || simData.awayTeam?.team_id;
      
      // Extract team colors
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
      
      if (this.gameId && typeof localStorage !== 'undefined') {
        localStorage.setItem('game_id', this.gameId);
      }
      gameStore.setGameId(this.gameId);
      
      // Set team IDs on scene for animation systems
      this.homeTeamId = homeId;
      this.awayTeamId = awayId;
      gameStore.setColors({
        home: homeColors,
        away: awayColors,
      });
      this.isFinal = simData.is_final;
      if (DEBUG_FLOW) {
        console.log(
          `✅ Simulated matchup: ${logHome} vs ${logAway}`
        );
        console.log("📦 First turn:", simData.turns?.[0]);
      }

      const homeLogoEl = document.getElementById('home-logo');
      const awayLogoEl = document.getElementById('away-logo');
      if (homeLogoEl) homeLogoEl.src = `/static/images/homepage-logos/${encodeURIComponent(homeTeam)}.png`;
      if (awayLogoEl) awayLogoEl.src = `/static/images/homepage-logos/${encodeURIComponent(awayTeam)}.png`;

      const homeFoulsEl = document.getElementById('home-fouls');
      const awayFoulsEl = document.getElementById('away-fouls');
      const clockEl = document.getElementById('game-clock');
      const quarterEl = document.getElementById('quarter');

      const positions = ["PG","SG","SF","PF","C"];
      // Filter out the ball and inactive players (those without a position)
      const actualPlayers = simData.players.filter(p => {
        const id = p.playerId ?? p.player_id;
        const isBall = id === "ball" || id === "Ball" || p.name === "ball" || p.name === "Ball";
        const hasPosition = p.pos !== null && p.pos !== undefined; // Only include players in current lineup
        
        if (!isBall && !hasPosition) {
          console.log(`🚫 Filtering out inactive player (no position): ${p.name} (${id})`);
        }
        
        return !isBall && hasPosition;
      });
      
      // Filtered active players from roster
      
      this.nameToId = Object.fromEntries(actualPlayers.map(p => [p.name, p.playerId ?? p.player_id]));
      this.playerInfo = Object.fromEntries(actualPlayers.map(p => [p.playerId ?? p.player_id, { name: p.name, team: p.team, pos: p.pos }]));
      
      // Reset player stats to 0 for all players (force clean slate)
      this.playerStats = {};
      simData.players.forEach(p => {
        const id = p.playerId ?? p.player_id;
        // Initialize all stats to 0 to prevent stats from previous games carrying over
        this.playerStats[id] = { 
          PTS: 0, F: 0, REB: 0, AST: 0, STL: 0, BLK: 0, TO: 0, DEF_A: 0, DEF_S: 0 
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
        const playerPhoto = player.photo || `/static/images/players/${playerId}.png`;
        image.src = playerPhoto;
        image.onerror = () => {
          image.src = '/static/images/players/default.png'; // Fallback image
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
        
        // Get team attributes from nested structure or old flat structure
        const homeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
        const awayTeamObj = typeof simData.away_team === 'object' ? simData.away_team : null;
        const homeAttrs = homeTeamObj?.attributes || simData.team_attributes?.[homeTeam] || {};
        const awayAttrs = awayTeamObj?.attributes || simData.team_attributes?.[awayTeam] || {};
        
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
      const liveScore = {
        [homeTeam]: isNewGame ? 0 : (simData.score?.[homeTeam] ?? 0),
        [awayTeam]: isNewGame ? 0 : (simData.score?.[awayTeam] ?? 0),
      };
      
      // Explicitly reset scoreboard UI for new games
      if (isNewGame) {
        emit('score:update', {
          home: 0,
          away: 0,
        });
      }
      let liveHomeFouls = simData.fouls?.home ?? 0;
      let liveAwayFouls = simData.fouls?.away ?? 0;
      let liveClock = simData.clock || '8:00';
      let liveQuarter = this.quarter;
      let livePeriodLabel = simData.period_label || `Q${this.quarter}`;

      const updateScoreboard = (turn = {}) => {
        const prevHome = liveScore[homeTeam];
        const prevAway = liveScore[awayTeam];

        // ``turn.score`` is authoritative. ``turn.points`` may appear in the
        // payload for context but must **not** be re-applied here to avoid
        // double counting.
        if (turn.score) {
          if (typeof turn.score[homeTeam] === 'number') liveScore[homeTeam] = turn.score[homeTeam];
          if (typeof turn.score[awayTeam] === 'number') liveScore[awayTeam] = turn.score[awayTeam];
        }

        const homeF = turn.homeFouls ?? turn.home_team_fouls ?? turn.fouls?.home;
        const awayF = turn.awayFouls ?? turn.away_team_fouls ?? turn.fouls?.away;
        if (typeof homeF === 'number') liveHomeFouls = homeF;
        if (typeof awayF === 'number') liveAwayFouls = awayF;

        if (turn.clock || turn.game_clock) liveClock = turn.clock || turn.game_clock;
        if (turn.quarter != null) liveQuarter = turn.quarter;
        if (turn.period_label) {
          livePeriodLabel = turn.period_label;
        } else if (turn.quarter != null) {
          livePeriodLabel = turn.quarter > 4 ? `OT${turn.quarter - 4}` : `Q${turn.quarter}`;
        }

        if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
        if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
        if (clockEl) clockEl.textContent = liveClock;
        if (quarterEl) quarterEl.textContent = livePeriodLabel;

        applyPlayerStats(turn);
        applyTeamStats(turn);

        if (liveScore[homeTeam] !== prevHome || liveScore[awayTeam] !== prevAway) {
          emit('score:update', {
            home: liveScore[homeTeam],
            away: liveScore[awayTeam],
          });
        }

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
      updateScoreboard({
        score: liveScore,
        homeFouls: liveHomeFouls,
        awayFouls: liveAwayFouls,
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
        
        // Show game completion popup
        const { showGameCompletionPopup } = await import('./utils/gameCompletionPopup.js');
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
          console.log(`🎮 Starting quarter ${this.quarter} (initial turns: ${simData.turns?.length || 0})`);
          await this.simulateTurnByTurn(simData, updateScoreboard);
          
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
            if (this.gameId && typeof localStorage !== 'undefined') {
              localStorage.setItem('game_id', this.gameId);
            }
            
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
              window.location.href = `/static/set-lineup.html?${params.toString()}`;
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
          
          const nextQ = this.quarter + 1;
          const params = new URLSearchParams(window.location.search);
          params.set('game_id', this.gameId);
          params.set('quarter', nextQ);
          params.set('period', `Q${nextQ}`);
          if (this.gameId && typeof localStorage !== 'undefined') {
            localStorage.setItem('game_id', this.gameId);
          }
          DEBUG_FLOW && console.log('➡️ Advancing to lineup', { nextQ, gameId: this.gameId });
          DEBUG_FLOW && console.log('skipToEnd at navigation:', this.skipToEnd);
          window.location.href = `/static/set-lineup.html?${params.toString()}`;
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
      console.log('🔄 Starting turn-by-turn simulation for quarter', this.quarter);
      
      const gameId = initialSimData.game_id;
      const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
      
      let quarterComplete = false;
      let turnCount = 0;
      let lastHomeScore = initialSimData.home_score || 0;
      let lastAwayScore = initialSimData.away_score || 0;
      let nextQuarterNumber = this.quarter + 1; // Will be updated when quarter completes
      
      // Initialize with any turns from the initial simulation (e.g., opening tip, inbound)
      const initialTurns = initialSimData.turns || [];
      
      // Animate initial turns first (opening tip, quarter start inbound, etc.)
      if (initialTurns.length > 0) {
        console.log(`🎬 Animating ${initialTurns.length} initial turns (opening tip/inbound)`);
        
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
          // Call /api/simulate-turn to get the next turn
          // Check for user overrides from quick adjust window
          const offenseOverride = window.nextOffenseOverride || null;
          const defenseOverride = window.nextDefenseOverride || null;
          
          // Clear overrides after reading (single-use)
          window.nextOffenseOverride = null;
          window.nextDefenseOverride = null;
          window.nextDefenseTypeOverride = null;
          window.nextDefenseAggressionOverride = null;
          
          // Clear visual selections in Playcall Center
          if (window.clearPlaycallOverrides) {
            window.clearPlaycallOverrides();
          }
          
          const response = await fetch('/api/simulate-turn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              game_id: gameId,
              offense_override: offenseOverride,
              defense_override: defenseOverride,
              mode: this.mode || 'single'
            })
          });
          
          if (!response.ok) {
            const errorData = await response.json();
            console.error('❌ /api/simulate-turn failed:', errorData);
            break;
          }
          
          const turnData = await response.json();
          
          // Check if quarter is complete
          if (turnData.quarter_complete || !turnData.turn) {
            console.log('✅ Quarter complete!', {
              time_remaining: turnData.time_remaining,
              turnCount,
              home_score: turnData.home_score,
              away_score: turnData.away_score
            });
            quarterComplete = true;
            
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
          let finalTurn = turn; // Track the final turn for Quick Adjust logic
          
          // Handle BATCH turns (e.g., HCO miss → OREB)
          if (turn.result_type === 'BATCH' && turn.batch_turns) {
            console.log(`🎬 Batch turn with ${turn.batch_turns.length} sub-turns`);
            
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
          
          console.log('🔍 Quick Adjust Check (SIMPLIFIED):', {
            nextOffenseTeam_from_API: turnData.offense_team,
            userTeamName,
            userHasOffenseNext,
            nextIsHCO,
            currentIsFastBreak,
            currentIsFreethrow,
            userTeamSide: this.userTeamSide
          });
          
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
          
          // Small delay between turns for readability (optional)
          await new Promise(resolve => setTimeout(resolve, 100));
          
        } catch (error) {
          console.error('❌ Error in turn-by-turn loop:', error);
          break;
        }
      }
      
      console.log(`🏁 Quarter ${this.quarter} finished! Total turns: ${turnCount}`);
      
      // Check if game should end or go to overtime
      // nextQuarterNumber is the quarter number the backend is ready for next
      // So the quarter we just finished is nextQuarterNumber - 1
      const quarterThatJustFinished = nextQuarterNumber - 1;
      const finalHomeScore = lastHomeScore;
      const finalAwayScore = lastAwayScore;
      const finalIsTied = finalHomeScore === finalAwayScore;
      
      console.log('🏁 Game completion check:', {
        quarterJustFinished: quarterThatJustFinished,
        nextQuarter: nextQuarterNumber,
        homeScore: finalHomeScore,
        awayScore: finalAwayScore,
        isTied: finalIsTied
      });
      
      // Game ends if:
      // 1. Q4 is complete and scores are NOT tied → game over
      // 2. Any OT is complete and scores are NOT tied → game over
      // Game continues if:
      // 1. Q4 is complete and scores ARE tied → go to OT
      // 2. OT is complete and scores ARE tied → go to next OT
      
      if (quarterThatJustFinished >= 4 && !finalIsTied) {
        // Game is over - finalize
        console.log('🏆 Game complete! Finalizing...');
        const finalize = async () => {
          const { finalizeGame } = await import('./finalizeGame.js');
          const finalScore = await finalizeGame({
            simData: {
              ...initialSimData,
              home_score: finalHomeScore,
              away_score: finalAwayScore,
              game_id: gameId,
              home_team: initialSimData.home_team,
              away_team: initialSimData.away_team
            },
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            game: this.game,
          });
          this.finalScore = finalScore;
          this.finalized = true;
          
          // Show game completion popup
          const { showGameCompletionPopup } = await import('./utils/gameCompletionPopup.js');
          const mode = this.tournamentId ? 'tournament' : (this.franchiseId ? 'franchise' : 'single');
          showGameCompletionPopup({
            gameId: gameId,
            mode: mode,
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            finalScore: finalScore
          });
          
          return finalScore;
        };
        await finalize();
        return; // Exit - game is over
      } else if (quarterThatJustFinished === 4 && finalIsTied) {
        // Q4 tied - go to OT
        console.log('⏰ Game tied after Q4! Going to overtime...');
        // Show locker room popup for OT
        const nextQ = nextQuarterNumber; // Should be 5 (first OT)
        const params = new URLSearchParams(window.location.search);
        params.set('game_id', this.gameId);
        params.set('quarter', nextQ);
        params.set('period', 'OT1');
        if (this.gameId && typeof localStorage !== 'undefined') {
          localStorage.setItem('game_id', this.gameId);
        }
        
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
          window.location.href = `/static/set-lineup.html?${params.toString()}`;
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
        if (this.gameId && typeof localStorage !== 'undefined') {
          localStorage.setItem('game_id', this.gameId);
        }
        
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
          window.location.href = `/static/set-lineup.html?${params.toString()}`;
        });
        return;
      } else {
        // Regular quarter complete (Q1-Q3) - show locker room popup
        console.log('✅ Quarter complete - showing locker room popup');
        const nextQ = this.quarter + 1;
        const params = new URLSearchParams(window.location.search);
        params.set('game_id', this.gameId);
        params.set('quarter', nextQ);
        params.set('period', `Q${nextQ}`);
        if (this.gameId && typeof localStorage !== 'undefined') {
          localStorage.setItem('game_id', this.gameId);
        }
        
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
          window.location.href = `/static/set-lineup.html?${params.toString()}`;
        });
        return;
      }
    }
  };
}
