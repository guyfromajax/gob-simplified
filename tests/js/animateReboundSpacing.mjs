import { animateRebound } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';

function createScene() {
  const delayedCalls = [];
  return {
    tweens: {
      add: ({ targets, x, y, onComplete }) => {
        if (targets) {
          targets.x = x;
          targets.y = y;
        }
        if (onComplete) onComplete();
        return { stop: () => {} };
      },
      killTweensOf: () => {}
    },
    game: { config: { width: 100, height: 50 } },
    time: {
      delayedCalls,
      delayedCall(ms, fn) {
        delayedCalls.push(ms);
        fn();
      }
    }
  };
}

function createSprite(team_id) {
  return {
    team_id,
    x: 0,
    y: 0,
    setPosition(x, y) {
      this.x = x;
      this.y = y;
    },
    setVisible() {}
  };
}

const scene = createScene();
const ballSprite = createSprite();
const playerSprites = {
  r1: createSprite('HOME'),
  p2: createSprite('HOME'),
  p3: createSprite('AWAY')
};

const animations = [
  { playerId: 'r1', movement: [{ coords: { x: 50, y: 25 } }] },
  { playerId: 'p2', movement: [{ coords: { x: 48, y: 24 } }] },
  { playerId: 'p3', movement: [{ coords: { x: 52, y: 26 } }] }
];

await animateRebound({
  scene,
  ballSprite,
  playerSprites,
  animations,
  rebounderId: 'r1',
  ballSpot: { x: 50, y: 25 }
});

function pixelToGrid(sprite) {
  return { x: sprite.x, y: 50 - sprite.y };
}

const r1 = pixelToGrid(playerSprites.r1);
const p2 = pixelToGrid(playerSprites.p2);
const p3 = pixelToGrid(playerSprites.p3);

const spacingValid =
  Math.abs(p2.x - r1.x) >= 3 &&
  Math.abs(p2.y - r1.y) >= 2 &&
  Math.abs(p3.x - r1.x) >= 3 &&
  Math.abs(p3.y - r1.y) >= 2 &&
  Math.abs(p3.x - p2.x) >= 3 &&
  Math.abs(p3.y - p2.y) >= 2;

console.log(
  JSON.stringify({
    delay: scene.time.delayedCalls[0],
    spacingValid,
    ballLocked: ballSprite.x === playerSprites.r1.x && ballSprite.y === playerSprites.r1.y
  })
);
