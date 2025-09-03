import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';
import { finalizeGame } from './finalizeGame.js';
import { emit } from './utils/eventBus.js';
import { appendToTextScroll } from './utils/textScroll.js';

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
      this.reboundInProgress = false;
      this.rebounderId = null;
    }

    init(data) {
        this.rosters = data.rosters;
        this.tournamentId = data.tournamentId;
        this.franchiseId = data.franchiseId;
        this.homeTeam = data.homeTeam;
        this.awayTeam = data.awayTeam;
        this.animate = data.animate;
        this.mode = data.mode;
        this.homeLineup = data.homeLineup || {};
        this.awayLineup = data.awayLineup || {};
        this.periodLabel = data.periodLabel;
        this.gameId = data.gameId || null;
        if (!this.gameId && typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
        this.quarter = data.quarter || 1;

        if (DEBUG_FLOW) {
          console.log("🧠 Game initialized with:", {
            rosters: this.rosters,
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            homeTeam: this.homeTeam,
            awayTeam: this.awayTeam,
            mode: this.mode,
            periodLabel: this.periodLabel,
          });
        }
      }


    async preload() {
      if (DEBUG_FLOW) console.log("✅ GameScene preloaded");
      if (this.animate) {
        this.load.image("ball", "/static/images/ball.png");
        const normalizeTeamName = (name) => name.toLowerCase().replace(/[\s\-]/g, '_');
        const teamId = normalizeTeamName(this.homeTeam);
        this.load.image("court-bg", `/static/images/courts/${teamId}.jpg`);
      }

    }

    async create() {
      if (DEBUG_FLOW) console.log("🎬 GameScene created");

      const homeStatsEl = document.getElementById('home-stats-body');
      const awayStatsEl = document.getElementById('away-stats-body');
      if (homeStatsEl) homeStatsEl.innerHTML = '';
      if (awayStatsEl) awayStatsEl.innerHTML = '';

      this.playerSprites = {};
      this.nameToId = {};
      this.playerInfo = {};
      this.playerStats = {};

    //   const homeTeam = this.homeTeam || this.rosters.homeRoster.team || this.rosters.homeRoster.team_name;
    //   const awayTeam = this.awayTeam || this.rosters.awayRoster.team || this.rosters.awayRoster.team_name;

      const homeTeam = this.rosters.homeRoster.team_name;
      const awayTeam = this.rosters.awayRoster.team_name;

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
      const logHome = simData.homeTeam?.name || simData.home_team;
      const logAway = simData.awayTeam?.name || simData.away_team;
      const homeId = simData.home_team_id || simData.homeTeam?.team_id;
      const awayId = simData.away_team_id || simData.awayTeam?.team_id;
      if (DEBUG_TEAMS) {
        console.log('Resolved team IDs:', { home_team_id: homeId, away_team_id: awayId });
        console.log('Team colors from simData:', {
          mode: this.mode,
          home: simData.home_team_colors,
          away: simData.away_team_colors,
        });
      }
      this.gameId = simData.game_id || this.gameId;
      if (this.gameId && typeof localStorage !== 'undefined') {
        localStorage.setItem('game_id', this.gameId);
      }
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
      this.nameToId = Object.fromEntries(simData.players.map(p => [p.name, p.playerId ?? p.player_id]));
      this.playerInfo = Object.fromEntries(simData.players.map(p => [p.playerId ?? p.player_id, { name: p.name, team: p.team, pos: p.pos }]));
      this.playerStats = {};
      simData.players.forEach(p => {
        const id = p.playerId ?? p.player_id;
        this.playerStats[id] = { PTS: 0, REB: 0, AST: 0 };
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

      const initTeamTable = (teamKey, bodyEl) => {
        positions.forEach(pos => {
          const player = simData.players.find(p => p.team === teamKey && p.pos === pos);
          const playerId = player?.playerId ?? player?.player_id;
          const tr = document.createElement('tr');
          const nameTd = document.createElement('td');
          const ptsTd = document.createElement('td');
          const rebTd = document.createElement('td');
          const astTd = document.createElement('td');
          nameTd.textContent = formatName(player?.name) || '';
          ptsTd.textContent = '0';
          rebTd.textContent = '0';
          astTd.textContent = '0';
          tr.append(nameTd, ptsTd, rebTd, astTd);
          bodyEl.appendChild(tr);
          this.rowRefs[teamKey][pos] = { nameCell: nameTd, ptsCell: ptsTd, rebCell: rebTd, astCell: astTd };
          if (playerId) {
            this.playerStats[playerId].cells = { pts: ptsTd, reb: rebTd, ast: astTd };
            this.currentLineup[teamKey][pos] = playerId;
          }
        });
      };

      initTeamTable('home', homeBody);
      initTeamTable('away', awayBody);

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
            const stats = this.playerStats[playerId] || { PTS: 0, REB: 0, AST: 0 };
            this.playerStats[playerId] = stats;
            row.ptsCell.textContent = stats.PTS;
            row.rebCell.textContent = stats.REB;
            row.astCell.textContent = stats.AST;
            stats.cells = { pts: row.ptsCell, reb: row.rebCell, ast: row.astCell };
          }
        });
      };

      const hydrateBoxScore = () => {
        // Use the baseline stats captured at the start of the quarter so the
        // table initially reflects pre-tip totals.
        const box = simData.start_box_score || {};
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
            const ps = this.playerStats[playerId] || { PTS: 0, REB: 0, AST: 0 };
            ps.PTS = pts;
            ps.REB = reb;
            ps.AST = ast;
            this.playerStats[playerId] = ps;
            lineup[pos] = playerId;
          });
          updateLineup(teamKey, lineup);
        });
      };

      hydrateBoxScore();

      if (this.animate) {
        this.playerSprites = loadPhaserPlayers(this, simData.players, {
          home: {
            player_ids: simData.players.filter(p => p.team === 'home').map(p => p.playerId ?? p.player_id),
            primary_color: simData.home_team_colors.primary_color,
            secondary_color: simData.home_team_colors.secondary_color,
          },
          away: {
            player_ids: simData.players.filter(p => p.team === 'away').map(p => p.playerId ?? p.player_id),
            primary_color: simData.away_team_colors.primary_color,
            secondary_color: simData.away_team_colors.secondary_color,
          },
        }, Phaser);
      }

      const applyPlayerStats = (turn = {}) => {
        if (turn.home_lineup) updateLineup('home', turn.home_lineup);
        if (turn.away_lineup) updateLineup('away', turn.away_lineup);

        if (turn.points && turn.shooter) {
          const shooterId = this.nameToId[turn.shooter];
          if (shooterId) {
            const ps = this.playerStats[shooterId];
            ps.PTS += turn.points;
            if (ps.cells?.pts) ps.cells.pts.textContent = ps.PTS;
          }
          if (turn.passer) {
            const passerId = this.nameToId[turn.passer];
            if (passerId) {
              const ps = this.playerStats[passerId];
              ps.AST += 1;
              if (ps.cells?.ast) ps.cells.ast.textContent = ps.AST;
            }
          }
        }

        const rebounderId =
          turn.rebounder_player_id ||
          turn.rebounderId ||
          turn.rebounder_id;
        if (rebounderId) {
          const ps = this.playerStats[rebounderId];
          if (ps) {
            ps.REB += 1;
            if (ps.cells?.reb) ps.cells.reb.textContent = ps.REB;
          }
        }
      };

      const formatTurnText = (turn = {}) => {
        const parts = [];
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

      // Live scoreboard state seeded from persisted game data
      const liveScore = {
        [homeTeam]: simData.score?.[homeTeam] ?? 0,
        [awayTeam]: simData.score?.[awayTeam] ?? 0,
      };
      let liveHomeFouls = simData.fouls?.home ?? 0;
      let liveAwayFouls = simData.fouls?.away ?? 0;
      let liveClock = simData.clock || '8:00';
      let liveQuarter = this.quarter;
      let livePeriodLabel = simData.period_label || `Q${this.quarter}`;

      const updateScoreboard = (turn = {}) => {
        const prevHome = liveScore[homeTeam];
        const prevAway = liveScore[awayTeam];

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

        if (liveScore[homeTeam] !== prevHome || liveScore[awayTeam] !== prevAway) {
          emit('score:update', {
            home: liveScore[homeTeam],
            away: liveScore[awayTeam],
          });
        }

        if (turn.text && turn.index !== this.lastTurnShown) {
          if (typeof window !== 'undefined' && window.TEXT_SCROLL_ENABLED) {
            appendToTextScroll(formatTurnText(turn));
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
      this.isPaused = false;
      this.skipToEnd = false;
      this.isSkipping = false;
      this.finalized = false;
      if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
          this.isPaused = !this.isPaused;
          if (this.isPaused) {
            this.tweens.pauseAll();
            pauseBtn.textContent = 'Resume';
          } else {
            this.tweens.resumeAll();
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
        return finalScore;
      };

      if (this.animate) {
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

          this.ballSprite = this.add.image(0, 0, "ball").setVisible(true).setDepth(1000).setScale(1);

          this.tweens.add({
            targets: this.ballSprite,
            scale: { from: 1, to: 1.3 },
            duration: 400,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
          });

          const quarterTurns = (simData.turns || []).filter(t => {
            const turnQ = t.quarter != null ? Number(t.quarter) : this.quarter;
            return turnQ === this.quarter;
          });
          if (DEBUG_FLOW) {
            console.log('🔢 quarterTurns length', quarterTurns.length);
          }
          if (quarterTurns.length === 0) {
            const total = Array.isArray(simData.turns) ? simData.turns.length : 0;
            console.warn(`⚠️ No turns found for quarter ${this.quarter} (total turns: ${total}). Navigation halted.`);
            return;
          }

          let animStart;
          if (DEBUG_FLOW) {
            animStart = Date.now();
            console.log('🚀 animateGameTurns start', animStart);
          }
          await animateGameTurns({
            scene: this,
            simData: { ...simData, turns: quarterTurns },
            playerSprites: this.playerSprites,
            ballSprite: this.ballSprite,
            onUpdate: updateScoreboard
          });
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
        if (this.isFinal) {
          await finalize();
        } else {
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
  };
}
