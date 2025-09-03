import { attachBallToPlayer, animateRebound, shootBall } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';
import { runPass } from '../../FrontEnd/static/js/phaser/animation/ballTween.js';
import { getCurrentOwner, getPendingOwner, clearPendingOwner } from '../../FrontEnd/static/js/phaser/ball/ballController.js';

function makeScene() {
  return {
    tweens: {
      add: ({ targets, x, y, duration, ease, onComplete, onStop }) => {
        if (targets && targets[0]) {
          targets[0].x = x;
          targets[0].y = y;
        }
        onComplete?.();
        return { once: () => {}, stop: () => onStop?.() };
      },
      killTweensOf: () => {}
    },
    time: { delayedCall: (ms, fn) => fn() },
    events: { emit: () => {}, once: () => {} },
    game: { config: { width: 100, height: 50 }, loop: { frame: 0 } },
    playerSprites: {
      a: { x: 0, y: 0, playerId: 'a', team: 'home', team_id: 'H' },
      b: { x: 10, y: 0, playerId: 'b', team: 'home', team_id: 'H' },
      c: { x: 20, y: 0, playerId: 'c', team: 'home', team_id: 'H' }
    },
    stateMachine: { is: () => false, transition: () => {} }
  };
}

const scene = makeScene();
const ballSprite = { x:0,y:0,setPosition(x,y){this.x=x;this.y=y;},setVisible(){},setDepth(){} };
scene.ballSprite = ballSprite;

const states = [];

attachBallToPlayer(scene, ballSprite, scene.playerSprites.a);
states.push({ step: 'attach', owner: getCurrentOwner(scene), pending: getPendingOwner(scene) });

await runPass(scene, { fromId: 'a', toId: 'b', duration: 0 });
states.push({ step: 'passComplete', owner: getCurrentOwner(scene), pending: getPendingOwner(scene) });
clearPendingOwner(scene);
states.push({ step: 'afterUpdate', owner: getCurrentOwner(scene), pending: getPendingOwner(scene) });

const shot = await shootBall({
  scene,
  ballSprite,
  fromCoords: { x: 0, y: 0 },
  startTimestamp: 0,
  result: 'MISS',
  shooterPos: 'PG',
  shooterId: 'b',
  shooterTeamId: 'H',
  homeTeamId: 'H'
});
states.push({ step: 'afterShot', owner: getCurrentOwner(scene), pending: getPendingOwner(scene) });

await animateRebound({
  scene,
  ballSprite,
  playerSprites: scene.playerSprites,
  animations: [],
  rebounderId: 'c',
  ballSpot: shot.grid,
  shooterId: 'b'
});
states.push({ step: 'afterRebound', owner: getCurrentOwner(scene), pending: getPendingOwner(scene) });

console.log(JSON.stringify(states));
