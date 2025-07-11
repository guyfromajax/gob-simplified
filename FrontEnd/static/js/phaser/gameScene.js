import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';

export function createGameScene(Phaser) {
  return class GameScene extends Phaser.Scene {
    constructor() {
      super("GameScene");
    }

    async preload() {
      console.log("✅ GameScene preloaded");
      this.load.image("ball", "/static/images/ball.png");
    }

    async create() {
      console.log("🎬 GameScene created");

      const homeTeam = sessionStorage.getItem("homeTeam") || "Four Corners";
      const awayTeam = sessionStorage.getItem("awayTeam") || "Bentley-Truman";

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
      console.log("📦 First turn:", simData.turns?.[0]);

      // 🏀 Load court background image based on home team ID
      const teamId = simData.home_team_id.toLowerCase(); // ensures lowercase for snake-case file names
      const courtKey = "court-bg";
      const courtPath = `/static/images/courts/${teamId}.jpg`;
      const fallbackPath = "/static/images/courts/default.jpg";

      // Load with fallback
      this.load.image(courtKey, courtPath);
      
      // Ensure animation only runs after everything is loaded and created
      this.load.once("complete", async () => {
        if (this.textures.exists(courtKey)) {
        this.add.image(0, 0, courtKey)
            .setOrigin(0)
            .setDisplaySize(this.game.config.width, this.game.config.height)
            .setDepth(0);
        } else {
        this.load.image(courtKey, fallbackPath);
        this.load.once("complete", () => {
            this.add.image(0, 0, courtKey)
            .setOrigin(0)
            .setDisplaySize(this.game.config.width, this.game.config.height)
            .setDepth(0);
        });
        this.load.start();
        }
    
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
    });
    }
  };
}
