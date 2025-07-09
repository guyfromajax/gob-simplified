
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { playTurnAnimation } from './animation/playTurnAnimation.js';
import { onAction } from './animation/onAction.js';
import { passBall, lockBallToPlayer } from './animation/ballManager.js';

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
        startingCoords: { x: 30, y: 25 },
        movement: [
          { timestamp: 0, coords: { x: 30, y: 25 }, action: "handle_ball" },
          { timestamp: 1000, coords: { x: 50, y: 50 }, action: "pass" }
        ],
        hasBallAtStep: [true, false] // For passer

      },
      {
        playerId: receiverId,
        pos: "SG",
        jersey: "2",
        startingCoords: { x: 60, y: 25 },
        movement: [
          { timestamp: 1000, coords: { x: 60, y: 25 }, action: "receive" },
          { timestamp: 2000, coords: { x: 70, y: 50 }, action: "shoot" }
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

    // Create ball sprite as a white circle
    this.ballSprite = this.add.circle(0, 0, 8, 0xffffff);
    this.ballSprite.setVisible(false);

    // Simulated pass logic
    const passStep = allPlayers[0].movement[1];
    const receiveStep = allPlayers[1].movement[0];

    lockBallToPlayer(this.ballSprite, this.playerSprites[playerId]);

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
