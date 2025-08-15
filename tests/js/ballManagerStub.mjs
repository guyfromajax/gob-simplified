export function lockBallToPlayer() {}
export const calls = [];
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export function shootBall(opts) {
  calls.push(opts);
  // return a fake landing spot so rebound logic can run in tests
  return Promise.resolve({ grid: { x: 0, y: 0 } });
}
export function animateRebound(opts) {
  calls.push({ type: 'rebound', opts });
}
