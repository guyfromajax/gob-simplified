import {
  animateRebound,
  animateKickoutReset,
  animatePutbackAttempt,
  calls
} from './ballManagerStub.mjs';

const PAUSE_MS = 400;

function makeScene() {
  return { ballAttachedToPlayerId: null };
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
  scene.ballAttachedToPlayerId = 'c';
  events.push({ type: 'attach', id: 'c' });

  await animateKickoutReset(scene, ball, 'c', 'pg', {}, 0);
  events.push({ type: 'detach', id: 'c' });
  scene.ballAttachedToPlayerId = 'pg';
  events.push({ type: 'attach', id: 'pg' });

  return { branch: 'kickout', pause: PAUSE_MS, attachments: { rebound: 'c', afterKickout: 'pg' }, events };
}

async function scenarioB(result) {
  const scene = makeScene();
  const ball = makeBall();
  const players = createPlayers();
  const events = [];

  await animateRebound({ scene, ballSprite: ball, playerSprites: players, animations: [], rebounderId: 'c', ballSpot: { x: 0, y: 0 } });
  scene.ballAttachedToPlayerId = 'c';
  events.push({ type: 'attach', id: 'c' });

  const outcome = await animatePutbackAttempt(scene, ball, 'c', { x: 0, y: 0 }, 0, result);
  events.push({ type: 'detach', id: 'c' });
  scene.ballAttachedToPlayerId = null;

  return { branch: 'putback', result, outcome, pause: 0, events };
}

const kickout = await scenarioA();
const putbackMake = await scenarioB('MAKE');
const putbackMiss = await scenarioB('MISS');

console.log(JSON.stringify({ scenarioA: kickout, scenarioB: { make: putbackMake, miss: putbackMiss }, calls }));
