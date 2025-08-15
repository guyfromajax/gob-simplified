import { shootBall } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';

function createScene() {
  const tweens = [];
  const scene = {
    tweens: {
      add: (cfg) => {
        tweens.push(cfg);
        cfg.onComplete && cfg.onComplete();
        return {};
      },
      killTweensOf: () => {}
    },
    time: { delayedCall: (ms, fn) => fn() },
    game: { config: { width: 100, height: 50 } }
  };
  scene._tweens = tweens;
  return scene;
}

async function run(isHomeTeam) {
  const scene = createScene();
  const ballSprite = { setPosition() {}, setVisible() {} };
  const shooterTeamId = isHomeTeam ? 1 : 2;
  await shootBall({
    scene,
    ballSprite,
    fromCoords: { x: 0, y: 0 },
    startTimestamp: 0,
    result: 'MAKE',
    shooterPos: 'PG',
    shooterId: 1,
    shooterTeamId,
    homeTeamId: 1
  });
  const last = scene._tweens[scene._tweens.length - 1];
  return { x: last.x, y: last.y };
}

const home = await run(true);
const away = await run(false);
console.log(JSON.stringify({ home, away }));
