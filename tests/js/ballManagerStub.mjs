export function lockBallToPlayer() {}
export const calls = [];
export function shootBall(opts) { calls.push(opts); return Promise.resolve(); }
