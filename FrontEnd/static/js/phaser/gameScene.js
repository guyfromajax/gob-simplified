import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';
import { finalizeGame } from './finalizeGame.js';
import { emit } from './utils/eventBus.js';

export function createGameScene(Phaser) {
  return class GameScene extends Phaser.Scene {
    constructor() {
      super("GameScene");
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

        console.log("🧠 Game initialized with:", {
          rosters: this.rosters,
          tournamentId: this.tournamentId,
          franchiseId: this.franchiseId,
          homeTeam: this.homeTeam,
          awayTeam: this.awayTeam,
          mode: this.mode,
        });
      }
      

    async preload() {
      console.log("✅ GameScene preloaded");
      if (this.animate) {
        this.load.image("ball", "/static/images/ball.png");
        const normalizeTeamName = (name) => name.toLowerCase().replace(/[\s\-]/g, '_');
        const teamId = normalizeTeamName(this.homeTeam);
        this.load.image("court-bg", `/static/images/courts/${teamId}.jpg`);
      }

    }

    async create() {
      console.log("🎬 GameScene created");

    //   const homeTeam = this.homeTeam || this.rosters.homeRoster.team || this.rosters.homeRoster.team_name;
    //   const awayTeam = this.awayTeam || this.rosters.awayRoster.team || this.rosters.awayRoster.team_name;

      const homeTeam = this.rosters.homeRoster.team_name;
      const awayTeam = this.rosters.awayRoster.team_name;

    console.log("📨 Sending /api/simulate request for:", homeTeam, "vs", awayTeam);

      const payload = { home_team: homeTeam, away_team: awayTeam };
      if (Object.keys(this.homeLineup).length) payload.home_lineup = this.homeLineup;
      if (Object.keys(this.awayLineup).length) payload.away_lineup = this.awayLineup;
      const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
      });


      if (!res.ok) {
        console.error("❌ Failed to fetch sim data:", res.statusText);
        return;
      }

      const simData = await res.json();
      console.log("📦 simData received:", simData);
      const logHome = simData.homeTeam?.name || simData.home_team;
      const logAway = simData.awayTeam?.name || simData.away_team;
      console.log(
        `✅ Simulated matchup: ${logHome} vs ${logAway}`
      );
      console.log("📦 First turn:", simData.turns?.[0]);

      const homeLogoEl = document.getElementById('home-logo');
      const awayLogoEl = document.getElementById('away-logo');
      if (homeLogoEl) homeLogoEl.src = `/static/images/homepage-logos/${encodeURIComponent(homeTeam)}.png`;
      if (awayLogoEl) awayLogoEl.src = `/static/images/homepage-logos/${encodeURIComponent(awayTeam)}.png`;

      const homeFoulsEl = document.getElementById('home-fouls');
      const awayFoulsEl = document.getElementById('away-fouls');
      const clockEl = document.getElementById('game-clock');
      const quarterEl = document.getElementById('quarter');

      const positions = ["PG","SG","SF","PF","C"];
      this.nameToId = Object.fromEntries(simData.players.map(p => [p.name, p.playerId]));
      this.playerInfo = Object.fromEntries(simData.players.map(p => [p.playerId, { name: p.name, team: p.team, pos: p.pos }]));
      this.playerStats = {};
      simData.players.forEach(p => {
        this.playerStats[p.playerId] = { PTS: 0, REB: 0, AST: 0 };
      });
      this.rowRefs = { home: {}, away: {} };
      this.currentLineup = { home: {}, away: {} };

      const homeBody = document.getElementById('home-stats-body');
      const awayBody = document.getElementById('away-stats-body');

      const initTeamTable = (teamKey, bodyEl) => {
        positions.forEach(pos => {
          const player = simData.players.find(p => p.team === teamKey && p.pos === pos);
          const playerId = player?.playerId;
          const tr = document.createElement('tr');
          const nameTd = document.createElement('td');
          const ptsTd = document.createElement('td');
          const rebTd = document.createElement('td');
          const astTd = document.createElement('td');
          nameTd.textContent = player?.name || '';
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
            row.nameCell.textContent = info.name;
            const stats = this.playerStats[playerId] || { PTS: 0, REB: 0, AST: 0 };
            this.playerStats[playerId] = stats;
            row.ptsCell.textContent = stats.PTS;
            row.rebCell.textContent = stats.REB;
            row.astCell.textContent = stats.AST;
            stats.cells = { pts: row.ptsCell, reb: row.rebCell, ast: row.astCell };
          }
        });
      };

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

        if ((turn.result_type === 'DREB' || turn.result_type === 'OREB') && turn.ball_handler) {
          const rebId = this.nameToId[turn.ball_handler];
          if (rebId) {
            const ps = this.playerStats[rebId];
            ps.REB += 1;
            if (ps.cells?.reb) ps.cells.reb.textContent = ps.REB;
          }
        } else if (turn.text) {
          const m = turn.text.match(/([A-Za-z\-\'\.\s]+) grabs the rebound/);
          if (m) {
            const name = m[1].trim();
            const rebId = this.nameToId[name];
            if (rebId) {
              const ps = this.playerStats[rebId];
              ps.REB += 1;
              if (ps.cells?.reb) ps.cells.reb.textContent = ps.REB;
            }
          }
        }
      };

      // Live scoreboard state
      const liveScore = { [homeTeam]: 0, [awayTeam]: 0 };
      let liveHomeFouls = 0;
      let liveAwayFouls = 0;
      let liveClock = '8:00';
      let liveQuarter = 1;

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

        if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
        if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
        if (clockEl) clockEl.textContent = liveClock;
        if (quarterEl) quarterEl.textContent = `Q:${liveQuarter}`;

        applyPlayerStats(turn);

        if (liveScore[homeTeam] !== prevHome || liveScore[awayTeam] !== prevAway) {
          emit('score:update', {
            home: liveScore[homeTeam],
            away: liveScore[awayTeam],
          });
        }
      };

      // Initialize scoreboard at tip-off
      updateScoreboard();

      const pauseBtn = document.getElementById('pause-btn');
      const skipBtn = document.getElementById('skip-btn');
      this.isPaused = false;
      this.skipToEnd = false;
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
      if (skipBtn) {
        skipBtn.addEventListener('click', () => {
          this.skipToEnd = true;
          this.tweens.killAll();
        });
      }

      const finalize = async () => {
        const finalScore = await finalizeGame({
          simData,
          tournamentId: this.tournamentId,
          franchiseId: this.franchiseId,
          game: this.game,
        });
        this.finalScore = finalScore;
      };

      if (this.animate) {
        const courtKey = "court-bg";

        const startAnimation = async () => {
          this.playerSprites = loadPhaserPlayers(this, simData.players, {
            home: {
              player_ids: simData.players.filter(p => p.team === "home").map(p => p.playerId),
              primary_color: simData.home_team_colors.primary_color,
              secondary_color: simData.home_team_colors.secondary_color
            },
            away: {
              player_ids: simData.players.filter(p => p.team === "away").map(p => p.playerId),
              primary_color: simData.away_team_colors.primary_color,
              secondary_color: simData.away_team_colors.secondary_color
            }
          }, Phaser);

          this.ballSprite = this.add.image(0, 0, "ball").setVisible(true).setDepth(1000).setScale(1);

          this.tweens.add({
            targets: this.ballSprite,
            scale: { from: 1, to: 1.3 },
            duration: 400,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
          });

          await animateGameTurns({
            scene: this,
            simData,
            playerSprites: this.playerSprites,
            ballSprite: this.ballSprite,
            onUpdate: updateScoreboard
          });

          console.log("✅ GameScene animation complete");
          await finalize();
        };

        if (this.textures.exists(courtKey)) {
          this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
          startAnimation();
        } else {
          this.load.once("complete", () => {
              this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
              startAnimation();
          });
          this.load.start();
        }
      } else {
        await finalize();
      }
    }
  };
}
