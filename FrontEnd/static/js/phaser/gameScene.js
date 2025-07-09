import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';

export class GameScene extends Phaser.Scene {
  constructor() {
    super("GameScene");
  }

  async preload() {
    console.log("✅ GameScene preloaded");
  }

  async create() {
    console.log("🎬 GameScene created");

    // 🧠 Get selected teams from sessionStorage (set via index.html)
    const homeTeam = sessionStorage.getItem("homeTeam") || "Four Corners";
    const awayTeam = sessionStorage.getItem("awayTeam") || "Bentley-Truman";

    // 🛰 Fetch sim data from backend
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

    // 🏀 Load court image dynamically by home team
    const teamId = simData.home_team_id.toLowerCase();
    const courtKey = "court-bg";
    const courtPath = `/static/images/courts/${teamId}.jpg`;
    const fallbackCourt = "/static/images/courts/default.jpg";

    try {
      const img = new Image();
      img.src = courtPath;
      img.onload = () => {
        this.textures.addBase64(courtKey, img.src);
        this.add.image(0, 0, courtKey).setOrigin(0).setDepth(0);
      };
      img.onerror = () => {
        this.load.image(courtKey, fallbackCourt);
        this.load.once("complete", () => {
          this.add.image(0, 0, courtKey).setOrigin(0).setDepth(0);
        });
        this.load.start();
      };
    } catch (e) {
      console.warn("⚠️ Failed to load court image:", e);
    }

    // 🧍 Build player containers
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

    // 🏀 Add ball sprite
    this.ballSprite = this.add.circle(0, 0, 8, 0xffffff).setVisible(false).setDepth(10);

    // 🔁 Animate all turns
    await animateGameTurns({
      scene: this,
      simData,
      playerSprites: this.playerSprites,
      ballSprite: this.ballSprite
    });

    console.log("✅ GameScene animation complete");
  }
}
