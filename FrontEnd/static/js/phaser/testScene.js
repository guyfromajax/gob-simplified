
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { playTurnAnimation } from './animation/playTurnAnimation.js';
import { onAction } from './animation/onAction.js';
import { passBall, lockBallToPlayer } from './animation/ballManager.js';
import { gridToPixels } from './utils/gridToPixels.js';


export function createTestScene(Phaser) {
  return class TestScene extends Phaser.Scene {
    constructor() {
      super("TestScene");
    }

  preload() {
    console.log("✅ TestScene preloaded");
  }

  create() {
    console.log("TestScene created")
    // Mock player data
    const playerId = "p1";
    const receiverId = "p2";

    const allPlayers = [
      {
        playerId,
        pos: "PG",
        jersey: "1",
        startingCoords: { x: 10, y: 10 },
        movement: [
          { timestamp: 0, coords: { x: 10, y: 10 }, action: "handle_ball" },
          { timestamp: 1000, coords: { x: 50, y: 25 }, action: "pass" }
        ],
        hasBallAtStep: [true, false] // For passer

      },
      {
        playerId: receiverId,
        pos: "SG",
        jersey: "2",
        startingCoords: { x: 30, y: 25 },
        movement: [
          { timestamp: 1000, coords: { x: 30, y: 25 }, action: "receive" },
          { timestamp: 4000, coords: { x: 70, y: 40 }, action: "shoot" } // ⏱ 4 seconds
        ],
        hasBallAtStep: [false, true] // For receiver
      }
    ];

    const teamInfo = {
      home: {
        player_ids: [playerId],
        primary_color: "#0074D9",
        secondary_color: "#FFFFFF"
      },
      away: {
        player_ids: [receiverId],
        primary_color: "#FF4136",
        secondary_color: "#FFFFFF"
      }
    };
  

    this.playerSprites = loadPhaserPlayers(this, allPlayers, teamInfo, Phaser);

    console.log("Player sprites loaded:", Object.keys(this.playerSprites));
    console.log("SG sprite (should be p2):", this.playerSprites["p2"]);
    const sgStart = gridToPixels(60, 25, this.game.config.width, this.game.config.height);
    this.add.circle(sgStart.x, sgStart.y, 6, 0xff0000).setDepth(5);

    const sgDest = gridToPixels(70, 50, this.game.config.width, this.game.config.height);
    this.add.circle(sgDest.x, sgDest.y, 6, 0x00ff00).setDepth(5); // 🟢 green dot

    // Create ball sprite as a white circle
    this.ballSprite = this.add.circle(0, 0, 8, 0xffffff);
    this.ballSprite.setVisible(false);

    // Simulated pass logic
    const passStep = allPlayers[0].movement[1];
    const receiveStep = allPlayers[1].movement[0];

    lockBallToPlayer(this.ballSprite, this.playerSprites[playerId]);

    if (!this.playerSprites) {
      console.error("❌ playerSprites is undefined!");
      return;
    }
    
    console.log("playTurnAnimation function:", playTurnAnimation);
    playTurnAnimation({
      scene: this,
      playerSprites: this.playerSprites,
      turnData: {
        animations: allPlayers
      },
      onAction: (action, sprite, timestamp) => {
        onAction(action, sprite, timestamp);

        if (action === "pass") {
          passBall({
            scene: this,
            ballSprite: this.ballSprite,
            fromCoords: passStep.coords,
            toCoords: receiveStep.coords,
            fromTimestamp: passStep.timestamp,
            toTimestamp: receiveStep.timestamp
          });
        }
      }
    });
  }
  }
}

export default createTestScene;


// import { TestScene } from "./phaser/TestScene.js";

// const config = {
//   type: Phaser.AUTO,
//   width: 1229,
//   height: 768,
//   backgroundColor: "#1e1e1e",
//   parent: "phaser-container",
//   scene: [TestScene],
// };

// const game = new Phaser.Game(config);
