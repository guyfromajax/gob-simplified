import runFreeThrowSequence from '../../FrontEnd/static/js/phaser/animation/freeThrow.js';
import { gridToPixels } from '../../FrontEnd/static/js/phaser/utils/gridToPixels.js';

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

const sceneHome = makeScene();
const playerSpritesHome = createPlayers();
sceneHome.playerInfo = createInfo();
const ballSpriteHome = makeBall();
let inboundCalled = false;
let reboundCalled = false;
let arcHeight;
await runFreeThrowSequence(sceneHome, {
  playerSprites: playerSpritesHome,
  ballSprite: ballSpriteHome,
  turnData: {
    result_type: 'FREE_THROW',
    offense_team_id: 'HOME',
    shooter_id: 'pg',
    shooter_pos: 'PG',
    attempts: ['MAKE'],
    animations: [
      { playerId: 'pg', movement: [ { timestamp:0, coords:{x:0,y:0} }, { timestamp:800, coords:{x:74,y:25} } ], duration:800 },
      { playerId: 'sg', movement: [ { timestamp:0, coords:{x:0,y:0} }, { timestamp:800, coords:{x:56,y:44} } ], duration:800 },
      { playerId: 'pgA', movement: [ { timestamp:0, coords:{x:0,y:0} }, { timestamp:800, coords:{x:54,y:37} } ], duration:800 },
      { playerId: 'ball', movement: [ { timestamp:0, coords:{x:74,y:25} }, { timestamp:500, coords:{x:91,y:25} } ], duration:500 }
    ]
  },
  helpers: {
    tweenBallTo: (scene, ball, target, opts) => { arcHeight = opts.arc.height; ball.x = target.x; ball.y = target.y; return Promise.resolve(); },
    runInboundSetup: () => { inboundCalled = true; return Promise.resolve(); },
    animateRebound: () => { reboundCalled = true; return Promise.resolve(); },
    attachBallToPlayer: () => {},
    detachBall: () => {},
  },
});

const pgDest = gridToPixels(74,25,100,50);
const sgDest = gridToPixels(56,44,100,50);
const dPgDest = gridToPixels(54,37,100,50);

const homeResult = {
  inboundCalled,
  reboundCalled,
  arcHeight,
  pg: { x: playerSpritesHome.pg.x, y: playerSpritesHome.pg.y },
  sg: { x: playerSpritesHome.sg.x, y: playerSpritesHome.sg.y },
  pgA: { x: playerSpritesHome.pgA.x, y: playerSpritesHome.pgA.y }
};

const sceneAway = makeScene();
const playerSpritesAway = createPlayers();
sceneAway.playerInfo = createInfo();
const ballSpriteAway = makeBall();
let inboundCalled2 = false;
let reboundCalled2 = false;
await runFreeThrowSequence(sceneAway, {
  playerSprites: playerSpritesAway,
  ballSprite: ballSpriteAway,
  turnData: {
    result_type: 'FREE_THROW',
    offense_team_id: 'AWAY',
    shooter_id: 'pgA',
    shooter_pos: 'PG',
    attempts: ['MISS'],
    animations: [
      { playerId: 'pgA', movement: [ { timestamp:0, coords:{x:0,y:0} }, { timestamp:800, coords:{x:27,y:25} } ], duration:800 },
      { playerId: 'ball', movement: [ { timestamp:0, coords:{x:27,y:25} }, { timestamp:500, coords:{x:9,y:25} } ], duration:500 }
    ]
  },
  helpers: {
    tweenBallTo: (scene, ball, target, opts) => Promise.resolve(),
    runInboundSetup: () => { inboundCalled2 = true; return Promise.resolve(); },
    animateRebound: () => { reboundCalled2 = true; return Promise.resolve(); },
    attachBallToPlayer: () => {},
    detachBall: () => {},
  }
});

const awayResult = {
  inboundCalled: inboundCalled2,
  reboundCalled: reboundCalled2,
};

console.log(JSON.stringify({ home: homeResult, away: awayResult, expected: { pgDest, sgDest, dPgDest } }));
