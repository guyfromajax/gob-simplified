export function attachBallToPlayer() {}
export const calls = [];
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export const INBOUND_DEBUG = false;
export function shootBall(opts) {
  calls.push(opts);
  // return a fake landing spot so rebound logic can run in tests
  return Promise.resolve({ grid: { x: 0, y: 0 } });
}
export function animateRebound(opts) {
  calls.push({ type: 'rebound', opts });
}

export function animateKickoutReset(scene, ballSprite, rebounderId, pgId, pass, duration) {
  calls.push({ type: 'kickoutReset', scene, ballSprite, rebounderId, pgId, pass, duration });
  return Promise.resolve();
}

export function animateInboundPass(scene, ballSprite, fromCoords, toCoords, startTs, endTs) {
  calls.push({
    type: 'inboundPass',
    scene,
    ballSprite,
    fromCoords,
    toCoords,
    startTs,
    endTs
  });
}
