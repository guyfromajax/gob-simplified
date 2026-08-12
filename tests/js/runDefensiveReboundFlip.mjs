import { animateRebound } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';
import {
  getCurrentOwner,
  initializeBallController,
} from '../../FrontEnd/static/js/phaser/animation/BallControllerAdapter.js';

globalThis.Audio = class {
  constructor() { this.dataset = {}; this.readyState = 4; this.currentTime = 0; }
  play() { return Promise.resolve(); }
  pause() {}
  addEventListener() {}
  removeEventListener() {}
};

function makeScene() {
  const log = {};
  return {
    tweens: {
      add: ({ onUpdate, onComplete, onStop }) => {
        if (onUpdate) onUpdate();
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {}
    },
    time: { delayedCall: (ms, fn) => fn() },
    events: {
      emit: (evt, payload) => { if (evt === 'possessionChange') log.event = payload.offenseTeamId; },
      on: () => {},
      off: () => {},
    },
    game: { config: { width: 100, height: 50 }, loop: { frame: 0 } },
    playerSprites: {
      pg: { x: 0, y: 0, playerId: 'pg', team: 'home', team_id: 'HOME' },
      pgA: { x: 0, y: 0, playerId: 'pgA', team: 'away', team_id: 'AWAY' }
    },
    playerInfo: {
      pg: { pos: 'PG', team_id: 'HOME', name: 'PG' },
      pgA: { pos: 'PG', team_id: 'AWAY', name: 'PG A' }
    },
    nameToId: { 'PG': 'pg', 'PG A': 'pgA' },
    possessionLog: log
  };
}

const scene = makeScene();
const ballSprite = { setPosition(){}, setVisible(){}, setDepth(){} };
for (const [playerId, sprite] of Object.entries(scene.playerSprites)) {
  Object.assign(sprite, { playerId, scene, active: true, depth: 1 });
}
initializeBallController(scene, ballSprite);
scene.offenseTeamId = 'HOME';
await animateRebound({
  scene,
  ballSprite,
  playerSprites: scene.playerSprites,
  animations: [],
  rebounderId: 'pgA',
  ballSpot: { x: 9, y: 25 },
  shooterId: 'pg',
});

console.log(JSON.stringify({ newOffense: scene.offenseTeamId, eventOffense: scene.possessionLog.event, attached: getCurrentOwner(scene) }));
