const enable = process.argv.includes('--enable');

globalThis.animation_config = { enableBallTween: enable };

const { generateBallTween } = await import('../../FrontEnd/static/js/phaser/animation/generateBallTween.js');

let tweenCalled = false;

const scene = {
  tweens: {
    add: (cfg) => {
      tweenCalled = true;
      cfg.onUpdate?.();
      cfg.onComplete?.();
      return { stop: () => {} };
    },
    killTweensOf: () => {},
  },
  game: { config: { width: 100, height: 100 } },
};

const ballSprite = {
  x: 0,
  y: 0,
  setPosition() {},
  setVisible() {},
  setDepth() {},
};
scene.ballSprite = ballSprite;

await generateBallTween({
  scene,
  ballSprite,
  startCoords: { x: 0, y: 0 },
  endCoords: { x: 1, y: 1 },
  startTimestamp: 0,
  endTimestamp: 10,
  type: 'pass',
});

console.log(JSON.stringify({ tweenCalled }));
