export function attachBallToPlayer(scene, ballSprite, playerSprite) {
  if (!ballSprite || !playerSprite) return;
  const x = playerSprite.x ?? 0;
  const y = playerSprite.y ?? 0;
  if (typeof ballSprite.setPosition === 'function') {
    ballSprite.setPosition(x, y);
  } else {
    ballSprite.x = x;
    ballSprite.y = y;
  }
  ballSprite.setVisible?.(true);
}

export function runPass() {
  return Promise.resolve();
}

export function animateRebound() {
  return Promise.resolve();
}

export function shootBall() {
  return Promise.resolve();
}

export default {
  attachBallToPlayer,
  runPass,
  animateRebound,
  shootBall,
};
