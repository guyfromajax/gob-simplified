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
    playerInfo: {},
    time: { delayedCall: (ms, fn) => fn() }
  };
}

function createSprite(team_id) {
  return { x: 0, y: 0, team_id, setPosition() {}, setVisible() {} };
}

async function runCase(startingTeamId) {
  calls.length = 0;
  const scene = createScene();
  const ballSprite = { setPosition() {}, setVisible() {} };
  const playerSprites = { p1: createSprite(startingTeamId) };
  const turnData = {
    starting_possession_team_id: startingTeamId,
    possession_team_id: startingTeamId,
    result_type: 'MAKE',
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
  return calls[0].shooterTeamId === calls[0].homeTeamId;
}

const homeResult = await runCase('HOME');
const awayResult = await runCase('AWAY');
console.log(JSON.stringify({ homeResult, awayResult }));
