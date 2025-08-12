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

        if (liveScore[homeTeam] !== prevHome || liveScore[awayTeam] !== prevAway) {
          emit('score:update', {
            home: liveScore[homeTeam],
            away: liveScore[awayTeam],
          });
        }
      };

      // Initialize scoreboard at tip-off
      updateScoreboard();

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
