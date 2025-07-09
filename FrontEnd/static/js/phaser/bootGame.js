import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { GameScene } from './gameScene.js';

const config = {
  type: Phaser.AUTO,
  width: 1229,
  height: 768,
  backgroundColor: "#1e1e1e",
  parent: "phaser-container",
  scene: [GameScene],
};

new Phaser.Game(config);


