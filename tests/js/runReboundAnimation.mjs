import { playTurnAnimation } from '../../FrontEnd/static/js/phaser/animation/turnAnimation.js';
import { calls } from './ballManagerStub.mjs';

function createScene() {
  return {
    skipToEnd: false,
    tweens: {
      add: ({ onUpdate, onComplete, onStop }) => {
        if (onUpdate) onUpdate();
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {}
    },
    game: { config: { width: 100, height: 50 } },
    playerInfo: { p1: { name: 'Rebounder' } },
    nameToId: { Rebounder: 'p1' },
    time: { delayedCall: (ms, fn) => fn() }
  };
}

function createSprite(team_id) {
  return { x: 0, y: 0, team_id, setPosition() {}, setVisible() {} };
}

const scene = createScene();
const ballSprite = { setPosition() {}, setVisible() {} };
const playerSprites = { p1: createSprite('HOME') };
const turnData = {
  starting_possession_team_id: 'HOME',
  possession_team_id: 'HOME',
  result_type: 'DREB',
  ball_handler: 'Rebounder',
  text: '',
  animations: [{
    playerId: 'p1',
    movement: [
      { timestamp: 0, coords: { x: 0, y: 0 }, action: 'handle_ball' },
      { timestamp: 10, coords: { x: 0, y: 0 }, action: 'shoot' }
    ],
    hasBallAtStep: [true, true]
  }]
};
const simData = { home_team_id: 'HOME' };

await playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite });
const shootOpts = calls.find(c => !c.type);
const reboundCall = calls.find(c => c.type === 'rebound');
console.log(JSON.stringify({
  resultMapped: shootOpts?.result,
  rebounderId: reboundCall?.opts?.rebounderId
}));
