export function lockBallToPlayer() {}
export const calls = [];
export const SHOT_DEBUG = false;
export function shootBall(opts) { calls.push(opts); return Promise.resolve(); }
