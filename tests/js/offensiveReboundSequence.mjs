import {
  animateRebound,
  animateKickoutReset,
  shootBall,
  calls
} from './ballManagerStub.mjs';
import { setCurrentOwner, clearCurrentOwner, getCurrentOwner } from '../../FrontEnd/static/js/phaser/ball/ballController.js';

const PAUSE_MS = 400;

function makeScene() {
  return {};
}

function makeBall() { return {}; }

function createPlayers() {
  return { pg: {}, c: {} };
}

async function scenarioA() {
  const scene = makeScene();
  const ball = makeBall();
  const players = createPlayers();
  const events = [];

  await animateRebound({ scene, ballSprite: ball, playerSprites: players, animations: [], rebounderId: 'c', ballSpot: { x: 0, y: 0 } });
  setCurrentOwner(scene, 'c');
  events.push({ type: 'attach', id: 'c' });

  await animateKickoutReset(scene, ball, 'c', 'pg', {}, 0);
  events.push({ type: 'detach', id: 'c' });
  setCurrentOwner(scene, 'pg');
  events.push({ type: 'attach', id: 'pg' });

  return { branch: 'kickout', pause: PAUSE_MS, attachments: { rebound: 'c', afterKickout: 'pg' }, events };
}

async function scenarioB(result) {
  const scene = makeScene();
  const ball = makeBall();
  const players = createPlayers();
  const events = [];

  await animateRebound({ scene, ballSprite: ball, playerSprites: players, animations: [], rebounderId: 'c', ballSpot: { x: 0, y: 0 } });
  setCurrentOwner(scene, 'c');
  events.push({ type: 'attach', id: 'c' });

  const outcome = await shootBall({
    scene,
    ballSprite: ball,
    fromCoords: { x: 0, y: 0 },
    startTimestamp: Date.now(),
    result: result,
    shooterPos: { x: 0, y: 0 },
    shooterId: 'c',
    shooterTeamId: 'home',
    homeTeamId: 'home',
    stepIndex: 0,
    turnIndex: 0
  });
  events.push({ type: 'detach', id: 'c' });
  clearCurrentOwner(scene);

  return { branch: 'putback', result, outcome, pause: 0, events };
}

const kickout = await scenarioA();
const putbackMake = await scenarioB('MAKE');
const putbackMiss = await scenarioB('MISS');

console.log(JSON.stringify({ scenarioA: kickout, scenarioB: { make: putbackMake, miss: putbackMiss }, calls }));
