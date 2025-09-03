const stateMap = new WeakMap();

function ensure(scene) {
  let s = stateMap.get(scene);
  if (!s) {
    s = { currentOwnerId: null, lastOwnerId: null, pendingOwnerId: null };
    stateMap.set(scene, s);
  }
  return s;
}

export function getCurrentOwner(scene) {
  return ensure(scene).currentOwnerId;
}

export function setCurrentOwner(scene, playerId) {
  const s = ensure(scene);
  s.currentOwnerId = playerId;
  if (playerId != null) {
    s.lastOwnerId = playerId;
  }
}

export function clearCurrentOwner(scene) {
  ensure(scene).currentOwnerId = null;
}

export function getLastKnownOwner(scene) {
  return ensure(scene).lastOwnerId;
}

export function getPendingOwner(scene) {
  return ensure(scene).pendingOwnerId;
}

export function setPendingOwner(scene, playerId) {
  ensure(scene).pendingOwnerId = playerId;
}

export function clearPendingOwner(scene) {
  ensure(scene).pendingOwnerId = null;
}

export function cancelBallTween(scene, ballSpriteOverride) {
  const s = ensure(scene);
  s.pendingOwnerId = null;
  const ballSprite = ballSpriteOverride || scene.ballSprite;
  if (scene?.tweens && ballSprite) {
    scene.tweens.killTweensOf(ballSprite);
  }
}

export default {
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner,
  getLastKnownOwner,
  getPendingOwner,
  setPendingOwner,
  clearPendingOwner,
  cancelBallTween
};
