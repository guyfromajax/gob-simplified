import { playTurnAnimation } from '../../FrontEnd/static/js/phaser/animation/turnAnimation.js';

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
    events: { emit: (evt, payload) => { if (evt === 'possessionChange') log.event = payload.offenseTeamId; } },
    game: { config: { width: 100, height: 50 }, loop: { frame: 0 } },
    playerSprites: {
      pg: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      pgA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' }
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
const simData = { home_team_id: 'HOME', away_team_id: 'AWAY', players: [] };
const turnData = {
  starting_possession_team_id: 'HOME',
  possession_team_id: 'HOME',
  result_type: 'MISS',
  ball_handler: 'PG A',
  animations: [
    {
      playerId: 'pg',
      movement: [
        { timestamp: 0, action: 'handle', coords: { x: 0, y: 0 } },
        { timestamp: 1, action: 'shoot', coords: { x: 0, y: 0 } }
      ],
      hasBallAtStep: [true, false]
    }
  ]
};

await playTurnAnimation({ scene, simData, playerSprites: scene.playerSprites, turnData, ballSprite });

console.log(JSON.stringify({ newOffense: scene.offenseTeamId, eventOffense: scene.possessionLog.event, attached: scene.ballAttachedToPlayerId }));
