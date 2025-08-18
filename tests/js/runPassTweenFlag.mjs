const enable = process.argv.includes('--enable');

globalThis.animation_config = { enableBallTween: enable };

const { runPass } = await import('../../FrontEnd/static/js/phaser/animation/ballTween.js');

let tweenCalled = false;

const ballSprite = {
  x: 0,
  y: 0,
  setPosition(x, y) {
    this.x = x;
    this.y = y;
  },
  setVisible() {},
  setDepth() {},
};

const scene = {
  tweens: {
    add: (cfg) => {
      tweenCalled = true;
      if (cfg.targets === ballSprite) {
        ballSprite.x = cfg.x;
        ballSprite.y = cfg.y;
      }
      cfg.onComplete?.();
      return { once: () => {}, stop: () => {} };
    },
    killTweensOf: () => {},
  },
  game: { loop: { frame: 0 }, config: { width: 100, height: 100 } },
  events: { emit: () => {} },
  ballSprite,
};

await runPass(scene, {
  startCoords: { x: 0, y: 0 },
  endCoords: { x: 10, y: 20 },
  duration: 10,
  easing: 'Linear',
});

console.log(
  JSON.stringify({ tweenCalled, x: ballSprite.x, y: ballSprite.y })
);
