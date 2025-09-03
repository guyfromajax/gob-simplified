import { attachBallToPlayer, animateRebound } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';
import { createGameStateMachine, States } from '../../FrontEnd/static/js/phaser/state/gameStateMachine.js';
import { getCurrentOwner } from '../../FrontEnd/static/js/phaser/ball/ballController.js';

function makeScene() {
  return {
    tweens: {
      add: ({ targets, x, y, duration, ease, onComplete, onStop }) => {
        if (targets && targets[0]) {
          targets[0].x = x;
          targets[0].y = y;
        }
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {}
    },
    time: { delayedCall: (ms, fn) => fn() },
    game: { config: { width: 100, height: 50 } },
    playerSprites: {
      a: { x: 0, y: 0, playerId: 'a', team: 'home', team_id: 'HOME' },
      b: { x: 0, y: 0, playerId: 'b', team: 'home', team_id: 'HOME' }
    },
    events: { emit: () => {} },
    rebounderId: 'a',
    stateMachine: createGameStateMachine(States.Rebound)
  };
}

const scene = makeScene();
const ballSprite = { setPosition(){}, setVisible(){}, setDepth(){} };

// Attempt to attach to non-rebounder while rebound in progress
attachBallToPlayer(scene, ballSprite, scene.playerSprites.b);
const first = getCurrentOwner(scene) ?? null;

// Animate rebound to attach to rebounder and clear flag
await animateRebound({
  scene,
  ballSprite,
  playerSprites: scene.playerSprites,
  animations: [],
  rebounderId: 'a',
  ballSpot: { x: 0, y: 0 }
});
const afterRebound = getCurrentOwner(scene);
const flagAfterRebound = scene.stateMachine.is(States.Rebound);

// Now that flag is cleared, attaching to another player works
attachBallToPlayer(scene, ballSprite, scene.playerSprites.b);
const final = getCurrentOwner(scene);

console.log(JSON.stringify({ first, afterRebound, flagAfterRebound, final }));
