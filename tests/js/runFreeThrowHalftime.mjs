import runFreeThrowSequence from '../../FrontEnd/static/js/phaser/animation/freeThrow.js';

function makeScene() {
  return {
    tweens: {
      add: ({ targets, x, y, onComplete, onStop }) => {
        if (Array.isArray(targets)) {
          targets.forEach(t => { t.x = x; t.y = y; });
        } else if (targets) {
          targets.x = x;
          targets.y = y;
        }
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {},
    },
    time: { delayedCall: (ms, fn) => fn() },
    game: { config: { width: 100, height: 50 } },
    events: { emit: () => {} },
    playerInfo: {},
    simData: { home_team_id: 'HOME', away_team_id: 'AWAY' },
  };
}

function createPlayers() {
  const ids = ['pg','sg','sf','pf','c','pgA','sgA','sfA','pfA','cA'];
  const sprites = {};
  for (const id of ids) sprites[id] = { x:0, y:0 };
  return sprites;
}

function createInfo() {
  return {
    pg: { pos:'PG', team_id:'HOME' },
    sg: { pos:'SG', team_id:'HOME' },
    sf: { pos:'SF', team_id:'HOME' },
    pf: { pos:'PF', team_id:'HOME' },
    c: { pos:'C', team_id:'HOME' },
    pgA: { pos:'PG', team_id:'AWAY' },
    sgA: { pos:'SG', team_id:'AWAY' },
    sfA: { pos:'SF', team_id:'AWAY' },
    pfA: { pos:'PF', team_id:'AWAY' },
    cA: { pos:'C', team_id:'AWAY' },
  };
}

function makeBall() {
  return { setPosition(x,y){this.x=x;this.y=y;}, setVisible(){}, setDepth(){}, x:0,y:0 };
}

const scene = makeScene();
const playerSprites = createPlayers();
scene.playerInfo = createInfo();
const ballSprite = makeBall();
let inboundSide;
let ballSpotX;
await runFreeThrowSequence(scene, {
  playerSprites,
  ballSprite,
  turnData: {
    result_type: 'FREE_THROW',
    offense_team_id: 'HOME',
    possession_team_id: 'AWAY',
    possession_flips: true,
    free_throws_remaining: 0,
    next_play_type: 'BASELINE_INBOUND',
    shooter_id: 'pg',
    shooter_pos: 'PG',
    attempts: ['MAKE'],
    animations: [
      { playerId: 'pg', movement: [ { timestamp:0, coords:{x:0,y:0} }, { timestamp:800, coords:{x:74,y:25} } ], duration:800 },
      { playerId: 'ball', movement: [ { timestamp:0, coords:{x:74,y:25} }, { timestamp:500, coords:{x:91,y:25} } ], duration:500 }
    ]
  },
  helpers: {
    tweenBallTo: (scene, ball, target) => { ball.x=target.x; ball.y=target.y; return Promise.resolve(); },
    runInboundSetup: ({ newOffenseSide }) => { inboundSide = newOffenseSide; ballSpotX = newOffenseSide === 'away' ? 98 : 3; return Promise.resolve(); },
    animateRebound: () => Promise.resolve(),
    attachBallToPlayer: () => {},
    detachBall: () => {},
    getOffenseSide: (scene, teamId) => teamId === scene.simData.home_team_id ? 'away' : 'home',
  },
});

console.log(JSON.stringify({ inboundSide, ballSpotX }));
