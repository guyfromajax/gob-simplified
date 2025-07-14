import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';

export function createGameScene(Phaser) {
  return class GameScene extends Phaser.Scene {
    constructor() {
      super("GameScene");
    }

    init(data) {
        this.rosters = data.rosters;
        this.tournamentId = data.tournamentId;
        this.homeTeam = data.homeTeam;
        this.awayTeam = data.awayTeam;

        console.log("🧠 Game initialized with:", {
          rosters: this.rosters,
          tournamentId: this.tournamentId,
          homeTeam: this.homeTeam,
          awayTeam: this.awayTeam,
        });
      }
      

    async preload() {
      console.log("✅ GameScene preloaded");
      this.load.image("ball", "/static/images/ball.png");
      const teamId = this.homeTeam.toLowerCase();
      this.load.image("court-bg", `/static/images/courts/${teamId}.jpg`);
    }

    async create() {
      console.log("🎬 GameScene created");

    //   const homeTeam = this.homeTeam || this.rosters.homeRoster.team || this.rosters.homeRoster.team_name;
    //   const awayTeam = this.awayTeam || this.rosters.awayRoster.team || this.rosters.awayRoster.team_name;

      const homeTeam = this.rosters.homeRoster.team_name;
      const awayTeam = this.rosters.awayRoster.team_name;

    console.log("📨 Sending /simulate request for:", homeTeam, "vs", awayTeam);

      const res = await fetch('/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ home_team: homeTeam, away_team: awayTeam })
      });


      if (!res.ok) {
        console.error("❌ Failed to fetch sim data:", res.statusText);
        return;
      }

      const simData = await res.json();
      console.log("📦 simData received:", simData);
      console.log(
        `✅ Simulated matchup: ${simData.home_team} vs ${simData.away_team}`
      );
      console.log("📦 First turn:", simData.turns?.[0]);

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
        ballSprite: this.ballSprite
        });

        console.log("✅ GameScene animation complete");

        // Extract score and winner
        const homeScore = simData.score?.[simData.home_team] || 0;
        const awayScore = simData.score?.[simData.away_team] || 0;
        const winner = homeScore > awayScore ? simData.home_team : simData.away_team;

        // POST to /tournament/save-result
        if (this.tournamentId) {
        try {
            const res = await fetch("/tournament/save-result", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tournament_id: this.tournamentId,
                game_id: simData._id,  // make sure _id is included in your /simulate response
                winner: winner
            })
            });

            if (!res.ok) {
            console.error("❌ Failed to save tournament result:", await res.text());
            } else {
            console.log("✅ Tournament result saved.");
            }
        } catch (err) {
            console.error("🚨 Error during tournament result save:", err);
        }
        }
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
    }
  };
}
